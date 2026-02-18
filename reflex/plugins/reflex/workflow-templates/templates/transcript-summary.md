---
name: transcript-summary
version: "1.0.0"
description: Batch summarize meeting transcripts into structured notes
tags: [transcript, summarize, batch, documentation]
variables:
  - name: transcript_pattern
    description: Glob pattern for transcript files to process
    default: "~/transcripts/**/*.txt"
  - name: output_directory
    description: Directory to save summary files
    default: "~/summaries"
  - name: parallel_workers
    description: Number of transcripts to process in parallel
    default: "3"
  - name: create_git_commit
    description: Whether to commit summaries to git after processing
    default: "true"
  - name: summary_format
    description: Format for summaries (structured-notes, bullet-points, executive)
    default: "structured-notes"
steps:
  - understand-requirements
  - batch-process
  - commit-and-summarize
---
<!-- BEGIN: Transcript Summary Workflow -->
## Transcript Summary Workflow

This workflow processes multiple meeting transcripts in parallel and generates structured summaries.

### 1. Understand Requirements

- Clarify the transcript location (confirm `{{transcript_pattern}}` is correct)
- Verify output directory exists or should be created: `{{output_directory}}`
- Confirm number of parallel workers: {{parallel_workers}}
- Ask about any specific focus areas or topics to emphasize in summaries
{{#create_git_commit}}- Confirm whether to create a git commit after processing{{/create_git_commit}}

### 2. Batch Process Transcripts

**Configure batch processing:**
- Pattern: `{{transcript_pattern}}`
- Operation: `summarize` (using /reflex:summarize-transcript)
- Parallel workers: {{parallel_workers}}
- Output location: `{{output_directory}}`
- Summary format: {{summary_format}}

**Find transcripts:**
- Use Glob to find files matching `{{transcript_pattern}}`
- Show count and list of transcripts to be processed
- Verify files are readable text files

**Create tasks:**
- For each transcript file:
  - Subject: "Summarize: <filename>"
  - Description: "Summarize transcript at <file_path> using {{summary_format}} format. Save to {{output_directory}}/<filename>-summary.md"
  - Active form: "Summarizing <filename>"
  - Metadata:
    - file_path: <full_path>
    - operation: "summarize"
    - format: "{{summary_format}}"
    - output_dir: "{{output_directory}}"
    - batch_id: <timestamp>

**Launch workers:**
- Run {{parallel_workers}} background agents using Task tool with `run_in_background: true`
- Each agent:
  1. Gets next pending task from TaskList
  2. TaskUpdate to mark in_progress
  3. Reads transcript file
  4. Invokes /reflex:summarize-transcript with transcript content
  5. Formats summary as {{summary_format}}:
     - **structured-notes**: ## Summary, ## Key Decisions, ## Action Items, ## Topics Discussed
     - **bullet-points**: Simple bullet list of key points
     - **executive**: Executive summary paragraph + highlights
  6. Saves summary to `{{output_directory}}/<basename>-summary.md`
  7. TaskUpdate to completed with output file path

**Track progress:**
- Use TaskList to show progress every 30 seconds
- Report: X/Y completed (Z in progress, W pending)
- Show estimated time remaining based on average processing time

**Handle errors:**
- If a task fails:
  - TaskUpdate with error details in metadata
  - Log the error but continue processing other files
  - Collect failed files for user review

**Completion:**
- Wait for all background agents to finish
- Generate summary report:
  - Total transcripts: <count>
  - Successfully processed: <count>
  - Failed: <count> (list files)
  - Output location: {{output_directory}}
  - Average processing time: <time>

### 3. Commit and Summarize

{{#create_git_commit}}
**Create git commit:**
- Stage all summary files in `{{output_directory}}`
- Commit with message:
  ```
  docs: add transcript summaries for <batch_date>

  Processed <count> transcripts:
  - <list of transcript names>

  Summaries saved to {{output_directory}}
  ```

**Provide summary:**
- List all generated summary files with paths
- Show high-level statistics (total meetings, key themes across all summaries)
- Mention any failed transcripts that need manual review
{{/create_git_commit}}

{{^create_git_commit}}
**Provide summary:**
- List all generated summary files with paths
- Show high-level statistics (total meetings, key themes across all summaries)
- Mention any failed transcripts that need manual review
- Remind user that summaries are in `{{output_directory}}` (not committed to git)
{{/create_git_commit}}

<!-- END: Transcript Summary Workflow -->
