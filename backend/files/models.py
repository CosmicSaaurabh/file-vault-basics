from django.db import models
import uuid
import os


def file_upload_path(instance, filename):
    """Generate file path for new file upload"""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join('uploads', filename)


class File(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.FileField(upload_to=file_upload_path)
    original_filename = models.CharField(max_length=255)
    file_type = models.CharField(max_length=100, db_index=True)  # Index for filtering
    size = models.BigIntegerField(db_index=True)  # Index for filtering
    uploaded_at = models.DateTimeField(auto_now_add=True, db_index=True)  # Index for filtering

    user_id = models.CharField(max_length=255, db_index=True)  # Index for user-scoping
    file_hash = models.CharField(max_length=64, db_index=True)  # Index for deduplication
    is_reference = models.BooleanField(default=False)
    original_file = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True,
                                      related_name='references')

    class Meta:
        ordering = ['-uploaded_at']
        # Add a composite index for common multi-field lookups
        indexes = [
            models.Index(fields=['user_id', 'file_type']),
            models.Index(fields=['user_id', 'size']),
        ]

    def __str__(self):
        return self.original_filename
