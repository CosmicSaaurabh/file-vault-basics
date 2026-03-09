import hashlib
from .models import File

def calculate_hash(file_obj):
    """Calculate SHA-256 hash of a file."""
    file_obj.seek(0)
    sha256_hash = hashlib.sha256()
    for chunk in file_obj.chunks():
        sha256_hash.update(chunk)
    file_obj.seek(0)
    return sha256_hash.hexdigest()

def create_file_record(user_id, file_obj):
    """
    Handles the business logic of creating a file record, including
    deduplication.
    Returns the created File instance.
    """
    file_hash = calculate_hash(file_obj)
    
    # Deduplication check
    existing_file = File.objects.filter(file_hash=file_hash, is_reference=False).first()

    if existing_file:
        # Create a reference to the existing file
        instance = File.objects.create(
            original_filename=file_obj.name,
            file_type=file_obj.content_type,
            size=file_obj.size,
            user_id=user_id,
            file_hash=file_hash,
            is_reference=True,
            original_file=existing_file,
            file=existing_file.file  # Point to the same physical file
        )
    else:
        # Create a new, original file
        instance = File.objects.create(
            original_filename=file_obj.name,
            file_type=file_obj.content_type,
            size=file_obj.size,
            user_id=user_id,
            file_hash=file_hash,
            is_reference=False,
            file=file_obj
        )
    return instance
