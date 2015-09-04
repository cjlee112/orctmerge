############################################################################
JSON based utilities for merging ReUsableText content and Socraticqs Data
############################################################################

This package contains basic utilities for integrating JSON data from

* ReUsableText: an extension of ReStructuredText, used to store
  structured content such as Open Response Concept Test (ORCT) questions,
  answers, error models etc.  Questions are identified by rustID,
  but error models did not have unique IDs.

* Socraticqs: a first-generation In Class Question System used to 
  collect student responses to ORCT questions.  Contains student
  responses, self-assessments and self-reporting of errors, stored in
  sqlite3.
  Data are identified by question_id.  Historically, the Socraticqs
  schema did not keep the mapping to rustID or specific error model IDs.

* Socraticqs2 (courselets.org): second-generation online platform for
  ORCT, containing both questions (identified by courseletsUL),
  concepts (conceptID), error models (courseletsError), responses etc.

Typical usages are 

* integrate ReUsableText content and Socraticqs response data to 
  produce JSON data that can be loaded directly into Socraticqs2
  (courselets.org).  This requires constructing the best possible
  mapping of the Socraticqs data onto the ReUsableText questions and
  error models, allowing for the possibility that the RUsT text may
  have changed slightly since the Socraticqs data were stored.

* integrate ReUsableText + Socraticqs data and Socraticqs2 identifiers
  to produce datasets suitable for external data analysis, as either
  JSON or CSV output.

Example usage::

  $ python orctmerge/jsonmerge.py course.db.json *_unit.json
  writing foo_unitmerge.json...
  writing bar_unitmerge.json...
