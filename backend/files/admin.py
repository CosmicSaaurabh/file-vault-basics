from django.contrib import admin
from .models import File

@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    list_display = ('original_filename', 'user_id', 'file_type', 'size', 'uploaded_at', 'is_reference')
    list_filter = ('file_type', 'user_id', 'is_reference')
    search_fields = ('original_filename', 'user_id')
    readonly_fields = ('id', 'uploaded_at', 'file_hash', 'original_file')
