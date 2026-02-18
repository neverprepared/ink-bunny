---
name: batch-process
description: Process multiple files in parallel using background agents
requires-tools: [Glob, TaskCreate, TaskUpdate, TaskList, Task]
variables:
  - name: batch_pattern
    description: Glob pattern for files to process (e.g., "~/transcripts/**/*.txt")
    default: ""
  - name: batch_operation
    description: Operation to perform on each file (e.g., "summarize", "ingest")
    default: "process"
  - name: parallel_workers
    description: Number of parallel workers to run concurrently
    default: "3"
  - name: output_location
    description: Where to save results (optional, operation-specific)
    default: ""
---
### {{step_number}}. Batch Process Files

**Find items to process:**
- Use Glob to find files matching `{{batch_pattern}}`
- Verify files exist and are readable
- Show count and sample of files to be processed

**Create tasks for each item:**
- For each file, use TaskCreate with:
  - `subject`: "{{batch_operation}}: <filename>"
  - `description`: Full path and operation details
  - `activeForm`: "Processing <filename>"
  - `metadata`: Include file_path, operation type, and batch_id

**Launch parallel workers:**
- Run {{parallel_workers}} background agents concurrently
- Each agent:
  1. Uses TaskList to find next pending task
  2. Uses TaskUpdate to mark task as in_progress
  3. Processes the file based on operation type from metadata
  4. Saves results{{#output_location}} to {{output_location}}{{/output_location}}
  5. Uses TaskUpdate to mark task as completed

**Track progress:**
- Use TaskList periodically to show progress (pending/in_progress/completed)
- Report any failures with error details in task metadata

**Wait for completion:**
- Monitor all background agents until all tasks are completed or failed
- Provide summary: total processed, succeeded, failed
