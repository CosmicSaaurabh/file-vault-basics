import time

from django.test import TestCase, override_settings
from rest_framework.test import APITestCase
from rest_framework import status
from .models import File
from .services import create_file_record
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.cache import cache

# --- Service Layer Unit Tests ---
class FileServiceTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user_id = "service-test-user"
        self.file_content = b"This is a service layer test file."

    def test_create_file_record_new(self):
        """
        Test that a new file is created correctly by the service.
        """
        file_obj = SimpleUploadedFile("new_file.txt", self.file_content)
        instance = create_file_record(user_id=self.user_id, file_obj=file_obj)
        
        self.assertIsNotNone(instance)
        self.assertEqual(File.objects.count(), 1)
        self.assertFalse(instance.is_reference)
        self.assertEqual(instance.user_id, self.user_id)
        self.assertIsNotNone(instance.file_hash)

    def test_create_file_record_duplicate(self):
        """
        Test that a duplicate file is created as a reference by the service.
        """
        # Create original
        original_file_obj = SimpleUploadedFile("original.txt", self.file_content)
        original_instance = create_file_record(user_id=self.user_id, file_obj=original_file_obj)
        
        # Create duplicate
        duplicate_file_obj = SimpleUploadedFile("duplicate.txt", self.file_content)
        duplicate_instance = create_file_record(user_id=self.user_id, file_obj=duplicate_file_obj)

        self.assertEqual(File.objects.count(), 2)
        self.assertTrue(duplicate_instance.is_reference)
        self.assertEqual(duplicate_instance.original_file, original_instance)
        self.assertEqual(duplicate_instance.file_hash, original_instance.file_hash)


# --- API Integration Tests ---
class FileAPITests(APITestCase):
    disable_throttling = True

    def setUp(self):
        self.user_1_id = "test-user-1"
        self.user_2_id = "test-user-2"
        cache.clear()
        self.file_content = b"This is a test file."
        self.another_file_content = b"Another file."

    def test_file_upload_success(self):
        file = SimpleUploadedFile("test.txt", self.file_content, content_type="text/plain")
        response = self.client.post('/api/files/', {'file': file}, HTTP_USERID=self.user_1_id)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(File.objects.count(), 1)
        self.assertEqual(File.objects.get().original_filename, 'test.txt')
        self.assertFalse(response.data['is_reference'])

    def test_deduplication_creates_reference(self):
        self.client.post('/api/files/', {'file': SimpleUploadedFile("test.txt", self.file_content)}, HTTP_USERID=self.user_1_id)
        response = self.client.post('/api/files/', {'file': SimpleUploadedFile("test_copy.txt", self.file_content)}, HTTP_USERID=self.user_1_id)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(File.objects.count(), 2)
        self.assertTrue(response.data['is_reference'])

    def test_user_isolation(self):
        self.client.post('/api/files/', {'file': SimpleUploadedFile("test.txt", self.file_content)}, HTTP_USERID=self.user_1_id)
        response = self.client.get('/api/files/', HTTP_USERID=self.user_2_id)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 0)

    @override_settings(MAX_STORAGE_PER_USER=50)
    def test_storage_quota_exceeded(self):
        large_file = SimpleUploadedFile("large.txt", b"This is a file that is definitely larger than fifty bytes.", content_type="text/plain")
        response = self.client.post('/api/files/', {'file': large_file}, HTTP_USERID=self.user_1_id)
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_filtering_by_file_type_and_search(self):
        self.client.post('/api/files/', {'file': SimpleUploadedFile("test.txt", self.file_content)}, HTTP_USERID=self.user_1_id)
        self.client.post('/api/files/', {'file': SimpleUploadedFile("document.pdf", b"PDF", "application/pdf")}, HTTP_USERID=self.user_1_id)
        time.sleep(1)

        response = self.client.get('/api/files/?file_type=application/pdf', HTTP_USERID=self.user_1_id)
        self.assertEqual(len(response.data['results']), 1)

        response = self.client.get('/api/files/?search=doc', HTTP_USERID=self.user_1_id)
        self.assertEqual(len(response.data['results']), 1)

    def test_storage_stats(self):
        self.client.post('/api/files/', {'file': SimpleUploadedFile("test.txt", self.file_content)}, HTTP_USERID=self.user_1_id)
        self.client.post('/api/files/', {'file': SimpleUploadedFile("test_copy.txt", self.file_content)}, HTTP_USERID=self.user_1_id)
        time.sleep(1)
        self.client.post('/api/files/', {'file': SimpleUploadedFile("another.txt", self.another_file_content)}, HTTP_USERID=self.user_1_id)

        response = self.client.get('/api/files/', HTTP_USERID=self.user_1_id)
        stats = response.data['storage_stats']

        self.assertEqual(stats['total_storage_used'], len(self.file_content) + len(self.another_file_content))
        self.assertEqual(stats['deduplication_savings'], len(self.file_content))

    def test_delete_file(self):
        upload_response = self.client.post('/api/files/', {'file': SimpleUploadedFile("test.txt", self.file_content)}, HTTP_USERID=self.user_1_id)
        file_id = upload_response.data['id']
        
        delete_response = self.client.delete(f'/api/files/{file_id}/', HTTP_USERID=self.user_1_id)
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)

    def test_missing_userid_header(self):
        response = self.client.get('/api/files/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
