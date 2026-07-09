from __future__ import annotations

"""OpenAI Stub 路由包。"""

from src.routes.openai.stubs.files import (
    add_upload_part,
    cancel_upload,
    complete_upload,
    create_upload,
    delete_file,
    list_files,
    retrieve_file,
    retrieve_file_content,
    upload_file,
)
from src.routes.openai.stubs.jobs import create_fine_tuning_job, list_fine_tuning_jobs, retrieve_fine_tuning_job, cancel_fine_tuning_job, list_fine_tuning_events, create_batch, list_batches, retrieve_batch, cancel_batch
from src.routes.openai.stubs.assistants import create_assistant, list_assistants, retrieve_assistant, modify_assistant, delete_assistant
from src.routes.openai.stubs.threads import create_thread, retrieve_thread, modify_thread, delete_thread, create_thread_message, list_thread_messages
from src.routes.openai.stubs.runs import create_run, list_runs, retrieve_run, cancel_run, submit_tool_outputs
from src.routes.openai.stubs.stores import create_vector_store, list_vector_stores, retrieve_vector_store, delete_vector_store, create_vector_store_file, list_vector_store_files
__all__ = [
    "upload_file",
    "list_files",
    "retrieve_file",
    "delete_file",
    "retrieve_file_content",
    "create_fine_tuning_job",
    "list_fine_tuning_jobs",
    "retrieve_fine_tuning_job",
    "cancel_fine_tuning_job",
    "list_fine_tuning_events",
    "create_batch",
    "list_batches",
    "retrieve_batch",
    "cancel_batch",
    "create_assistant",
    "list_assistants",
    "retrieve_assistant",
    "modify_assistant",
    "delete_assistant",
    "create_thread",
    "retrieve_thread",
    "modify_thread",
    "delete_thread",
    "create_thread_message",
    "list_thread_messages",
    "create_run",
    "list_runs",
    "retrieve_run",
    "cancel_run",
    "submit_tool_outputs",
    "create_vector_store",
    "list_vector_stores",
    "retrieve_vector_store",
    "delete_vector_store",
    "create_vector_store_file",
    "list_vector_store_files",
    "create_upload",
    "add_upload_part",
    "complete_upload",
    "cancel_upload",
]
