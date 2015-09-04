import json
import codecs
import csv


def load_json(infile, encoding='utf-8'):
    'read JSON file with unicode support'
    with codecs.open(infile, 'r', encoding=encoding) as ifile:
        data = json.load(ifile)
    return data

def dump_json(outfile, data, encoding='utf-8'):
    'write JSON file with unicode support'
    with codecs.open(outfile, 'w', encoding=encoding) as ofile:
        json.dump(data, ofile)
    
def socraticqs_report(questions):
    'print id, title, #responses, date from socraticqs question data'
    for l in questions:
        for q in l:
            print '%d\t%s\t%d\t%s' % (q['question_id'], q['title'],
                                len(q['responses']), q['date_added'])

def filter_socraticqs(questions):
    'get list of questions that have student responses'
    out = []
    for l in questions:
        for q in l:
            if q['responses']:
                out.append(q)
    return out

def map_socraticqs(orctIndex, socraticqsData):
    'tag Socraticqs questions with rustID based on best title match'
    for q in socraticqsData:
        try:
            q['rustID'] = orctIndex[q['title']]
        except KeyError:
            print 'no match found for %d %s' %(q['question_id'], q['title'])

def map_error_models(errors, socraticqsErrors):
    'map old socraticqs error models to ORCT schema'
    index = PhraseIndex(enumerate(errors))
    d = {}
    for em in socraticqsErrors:
        if '(ABORT)' in em['belief'] or '(FAIL)' in em['belief']:
            d[em['error_id']] = em['belief']
        else: # map to an error in our index
            d[em['error_id']] = index[em['belief']]
    return d
            
def inject_responses(orctDict, socraticqsData):
    'map response data from socraticqs into ORCT in blocks list'
    orctIndex = index_questions(orctDict)
    injections = filter_socraticqs(socraticqsData)
    map_socraticqs(orctIndex, injections)
    for q in injections:
        try:
            rustID = q['rustID']
        except KeyError:
            continue
        target = orctDict[rustID]
        if 'tests' not in target:
            print 'WARNING: %s defines no "tests" conceptID relation.' \
              % rustID
        print 'copying %d responses to %s...\n\t%s\n\t%s\n' \
          %(len(q['responses']), rustID, q['title'], target['title'])
        errorModels = map_error_models(target.get('error', ()), q['errors'])
        responses = target.setdefault('responses', [])
        for r in q['responses']:
            rnew = r.copy()
            errors = []
            for se in r['errors']:
                senew = se.copy()
                senew['error_id'] = errorModels[se['error_id']]
                errors.append(senew)
            rnew['errors'] = errors
            responses.append(rnew)

def choose_default_answer(questions):
    'just use the first answer from RUsT answer(s) for each question'
    for q in questions:
        q['answer'] = q['answer'][0]

def canonicalize_concept_id(questions, attr='tests'):
    'unpack attr list and convert to wikipedia ID format'
    for q in questions:
        if attr not in q:
            continue
        l = q[attr]
        if isinstance(l, str):
            l = [l]
        out = []
        for s in l:
            for t in s.split(','): # treat as comma separated list
                t = t.strip() # remove whitespace
                out.append(' '.join(t.split('_'))) # convert to wikipedia fmt
        q[attr] = out
                                        
def get_questions(blocks, questions=None):
    'filter questions from list of block dicts'
    if questions is None:
        questions = {}
    for q in blocks:
        if q['kind'] == 'question':
            questions[q['rustID']] = q
    return questions
            
def index_questions(questions):
    'build a phrase index for dict of questions'
    l = []
    for rustID, q in questions.items():
        l.append((rustID, q['title']))
    return PhraseIndex(l)
            
class PhraseIndex(object):
    'approximate text matching implemented with dict-like query interface'
    def __init__(self, t, nword=2):
        'construct phrase index for list of entries of the form [(id, text),]'
        self.nword = nword
        d = {}
        self.sizes = {}
        for i, text in t:
            n, l = self.get_phrases(text)
            self.sizes[i] = n # save numbers of phrases
            for j in range(n): # index all phrases in this text
                phrase = tuple(l[j:j + nword])
                try:
                    d[phrase].append(i)
                except KeyError:
                    d[phrase] = [i]
        self.d = d

    def get_phrases(self, text):
        'split into words, handling case < nword gracefully'
        l = text.split()
        if len(l) > self.nword:
            return len(l) - self.nword + 1, l
        else: # handle short phrases gracefully to allow matching
            return 1, l

    def __getitem__(self, text):
        'find entry with highest phrase match fraction'
        n, l = self.get_phrases(text)
        counts = {}
        for j in range(n):
            phrase = tuple(l[j:j + self.nword])
            for i in self.d.get(phrase, ()):
                counts[i] = counts.get(i, 0)  + 1
        if not counts:
            raise KeyError
        l = []
        for i, c in counts.items(): # compute match fractions
            l.append((c / float(self.sizes[i]), i))
        l.sort()
        return l[-1][1] # return id with highest match fraction


        
def mergefiles(socraticqsfile, orctfiles):
    'inject socraticqs response data into ORCT content files'
    orctData = []
    orctDict = {}
    for orctfile in orctfiles:
        l = load_json(orctfile)
        get_questions(l, orctDict)
        orctData.append(l)
    socraticqsData = load_json(socraticqsfile)
    inject_responses(orctDict, socraticqsData['questions'])
    choose_default_answer(orctDict.values())
    canonicalize_concept_id(orctDict.values())
    for i,orctfile in enumerate(orctfiles):
        outfile = orctfile.split('.')[0] + 'merge.json'
        print 'writing %s...' % outfile
        dump_json(outfile, orctData[i])


def load_courselets_index(jsonfile, key=-1, val=0):
    d = {}
    for t in load_json(jsonfile):
        d[t[key]] = t[val]
    return d

def load_title_error_indices(titleFile, errorFile):
    titleIndex = load_courselets_index(titleFile)
    errorIndex = load_courselets_index(errorFile)
    return titleIndex, errorIndex

def add_courselet_ids(questions, titleIndex, errorIndex):
    'add courseletsUL and courseletsError mappings to ORCT dicts'
    nq = ne = 0
    for q in questions:
        try:
            q['courseletsUL'] = titleIndex[q['title']]
            nq += 1
        except KeyError:
            print 'warning: no courseletsUL for %s' % q['title']
        for i, e in enumerate(q.get('error', ())):
            try:
                conceptID = errorIndex[e]
                q.setdefault('courseletsError', {})[i] = conceptID
                ne += 1
            except KeyError:
                print 'warning: no courselets error matching "%s"' % e
    print 'Saved %d courseletsUL and %d courseletsError mappings' % (nq, ne)

def add_courselet_ids_to_files(titleFile, errorFile, orctFiles):
    'add courseletsUL and courseletsError mappings to a set of ORCT files'
    titleIndex, errorIndex = load_title_error_indices(titleFile, errorFile)
    for orctFile in orctFiles:
        questions = load_json(orctFile)
        add_courselet_ids(questions, titleIndex, errorIndex)
        print 'writing %s...' % orctFile
        dump_json(orctFile, questions) # save the updated data

def get_error_dicts(q):
    'return list of question errors in form [dict(courseletsError=X, text=Y)]'
    errors = []
    for i, e in enumerate(q.get('error', ())):
        d = dict(text=e)
        try:
            d['courseletsError'] = q['courseletsError'][str(i)]
        except KeyError:
            pass
        errors.append(d)
    return errors

def index_courselets_generic_errors(genericEM,
        columns=('courseletsError', 'isAbort', 'isFail', 'text')):
    'return sorted list of dict representing generic error models'
    genericEM.sort() # ensure canonical order of ascending conceptID
    genericIndex = PhraseIndex(list(enumerate([t[-1] for t in genericEM])))
    genericEMdicts = []
    for t in genericEM:
        d = {}
        for i, col in enumerate(columns):
            d[col] = t[i]
        genericEMdicts.append(d)
    return genericEMdicts, genericIndex

def get_response_tuple(d, columns):
    'build tuple of data from dict as specified by columns list'
    l = []
    for c in columns:
        keys = c.split('.')
        lookup = d
        try:
            for k in keys:
                if isinstance(lookup, list):
                    k = int(k)
                s = lookup = lookup[k]
        except (KeyError, IndexError):
            s = 'NULL'
        l.append(s)
    return tuple(l)
        
csvColumnsDefault = (
    'q.courseletsUL',
    'q.rustID',
    'r.question_id',
    'q.title',
    'q.tests.0',
    'r.username',
    'r.answer',
    'r.confidence',
    'r.selfeval',
    'r.criticisms',
    'r.submit_time',
    'genericErrors.0.courseletsError',
    'genericErrors.0.text',
    'genericErrors.0.status',
    'genericErrors.1.courseletsError',
    'genericErrors.1.text',
    'genericErrors.1.status',
    'genericErrors.2.courseletsError',
    'genericErrors.2.text',
    'genericErrors.2.status',
    'genericErrors.3.courseletsError',
    'genericErrors.3.text',
    'genericErrors.3.status',
    'genericErrors.4.courseletsError',
    'genericErrors.4.text',
    'genericErrors.4.status',
    'errors.0.courseletsError',
    'errors.0.text',
    'errors.0.status',
    'errors.1.courseletsError',
    'errors.1.text',
    'errors.1.status',
    'errors.2.courseletsError',
    'errors.2.text',
    'errors.2.status',
    'errors.3.courseletsError',
    'errors.3.text',
    'errors.3.status',
    'errors.4.courseletsError',
    'errors.4.text',
    'errors.4.status',
)

def get_response_tuples(questions, genericEM=[], columns=csvColumnsDefault,
                        **kwargs):
    'generate tuples for each response as specified by columns'
    genericEMdicts, genericIndex = index_courselets_generic_errors(genericEM)
    for q in questions:
        errors = get_error_dicts(q)
        for r in q['responses']:
            for d in genericEMdicts: # reset generic errors to default status
                d['status'] = 0
            for d in errors: # reset question errors to default status
                d['status'] = 0
            for se in r.get('errors', ()): # mark errors that occurred
                error_id = se['error_id']
                if isinstance(error_id, int): # question-specific error
                    errors[error_id]['status'] = 1
                else: # generic error
                    generic_id = genericIndex[error_id]
                    genericEMdicts[generic_id]['status'] = 1
            d = dict(q=q, r=r, errors=errors, genericErrors=genericEMdicts)
            d.update(kwargs) # include extra args for tuple output
            yield get_response_tuple(d, columns)

def json_to_csv(orctFile, genericEMfile='generic_em.json',
                columns=csvColumnsDefault, header=True, **kwargs):
    'convert JSON unitmerge file to CSV using specified columns'
    questions = load_json(orctFile)
    genericEM = load_json(genericEMfile)
    outfile = orctFile.split('.')[0] + '.csv'
    print 'writing %s...' % outfile
    with codecs.open(outfile, 'w', encoding='utf-8') as ofile:
        csvwriter = csv.writer(ofile)
        if header: # provide header enumerating our columns
            csvwriter.writerow(columns)
        for t in get_response_tuples(questions, genericEM, columns, **kwargs):
            csvwriter.writerow(t)
    
                    
if __name__ == '__main__':
    import sys
    mergefiles(sys.argv[1], sys.argv[2:])


