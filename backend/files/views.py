from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.response import Response
from .models import File
from .serializers import FileSerializer
from .services import create_file_record # Import the service layer
from django.db.models import Sum
from django.conf import settings

class FileViewSet(viewsets.ModelViewSet):
    queryset = File.objects.all()
    serializer_class = FileSerializer

    def get_queryset(self):
        user_id = self.request.headers.get('UserId')
        if not user_id:
            return File.objects.none()

        # Start with a base queryset for the user
        queryset = File.objects.filter(user_id=user_id)
        
        # Use a dictionary to map query params to model fields for cleaner filtering
        filter_mappings = {
            'search': 'original_filename__icontains',
            'file_type': 'file_type__exact',
            'min_size': 'size__gte',
            'max_size': 'size__lte',
            'start_date': 'uploaded_at__gte',
            'end_date': 'uploaded_at__lte',
        }

        for param, field in filter_mappings.items():
            value = self.request.query_params.get(param)
            if value:
                queryset = queryset.filter(**{field: value})
        
        return queryset

    def list(self, request, *args, **kwargs):
        user_id = request.headers.get('UserId')
        if not user_id:
            return Response({'error': 'UserId header is required'}, status=status.HTTP_400_BAD_REQUEST)

        queryset = self.get_queryset()
        
        # Optimize storage stats calculation
        user_files = File.objects.filter(user_id=user_id)
        total_storage_used = user_files.filter(is_reference=False).aggregate(total=Sum('size'))['total'] or 0
        potential_storage_used = user_files.aggregate(total=Sum('size'))['total'] or 0
        
        storage_stats = {
            'total_storage_used': total_storage_used,
            'storage_quota': settings.MAX_STORAGE_PER_USER,
            'deduplication_savings': potential_storage_used - total_storage_used,
        }

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data['storage_stats'] = storage_stats
            return response

        serializer = self.get_serializer(queryset, many=True)
        return Response({'results': serializer.data, 'storage_stats': storage_stats})

    def retrieve(self, request, *args, **kwargs):
        if not request.headers.get('UserId'):
            return Response({'error': 'UserId header is required'}, status=status.HTTP_400_BAD_REQUEST)
        return super().retrieve(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        user_id = request.headers.get('UserId')
        file_obj = request.FILES.get('file')

        if not file_obj:
            return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)
        if not user_id:
            return Response({'error': 'UserId header is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Check storage quota
        user_storage = File.objects.filter(user_id=user_id, is_reference=False).aggregate(total_size=Sum('size'))['total_size'] or 0
        if user_storage + file_obj.size > settings.MAX_STORAGE_PER_USER:
            return Response({'error': 'Storage Quota Exceeded'}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        # Use the service layer to handle file creation and deduplication
        instance = create_file_record(user_id=user_id, file_obj=file_obj)
        
        # Serialize the created instance for the response
        serializer = self.get_serializer(instance)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def destroy(self, request, *args, **kwargs):
        if not request.headers.get('UserId'):
            return Response({'error': 'UserId header is required'}, status=status.HTTP_400_BAD_REQUEST)
        return super().destroy(request, *args, **kwargs)
