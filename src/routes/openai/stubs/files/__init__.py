from __future__ import annotations

"""OpenAI Files + Vector Stores stub 端点集合。"""

from src.routes.openai.stubs.files.files_impl import (
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
from src.routes.openai.stubs.files.stores_impl import (
    create_vector_store,
    create_vector_store_file,
    delete_vector_store,
    list_vector_store_files,
    list_vector_stores,
    retrieve_vector_store,
)

__all__ = [
    "upload_file",
    "list_files",
    "retrieve_file",
    "delete_file",
    "retrieve_file_content",
    "create_upload",
    "add_upload_part",
    "complete_upload",
    "cancel_upload",
    "create_vector_store",
    "list_vector_stores",
    "retrieve_vector_store",
    "delete_vector_store",
    "create_vector_store_file",
    "list_vector_store_files",
]
