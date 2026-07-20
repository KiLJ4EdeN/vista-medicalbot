---
name: document_analysis
description: Analyze a session PDF or medical image with OCR/VLM while preserving uncertainty.
---

# Document Analysis

Use `inspect_session_file` only for a file listed in the current session
context. Pass its exact upload ID and a focused instruction describing what to
extract or analyze.

Transcribe measurements, units, labels, and negations carefully. Distinguish
visible document content from interpretation. Image quality and OCR can cause
errors, so mention uncertainty when text is unclear. Do not claim that an image
or report establishes a diagnosis by itself.
