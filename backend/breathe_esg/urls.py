from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from rest_framework_simplejwt.views import TokenRefreshView


class SPAView(TemplateView):
    """Serve the React SPA index.html for any non-API route."""
    def get_template_names(self):
        return []

    def get(self, request, *args, **kwargs):
        from django.http import FileResponse, Http404
        import os
        index = settings.FRONTEND_BUILD_DIR / 'index.html'
        if index.exists():
            return FileResponse(open(index, 'rb'), content_type='text/html')
        # Fallback when frontend hasn't been built yet (dev mode)
        from django.http import HttpResponse
        return HttpResponse(
            '<h2>Frontend not built yet.</h2><p>Run <code>npm run build</code> in the frontend/ directory.</p>',
            status=200
        )


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/', include('apps.organizations.urls')),
    path('api/', include('apps.ingestion.urls')),
    path('api/', include('apps.emissions.urls')),
    path('api/', include('apps.audit.urls')),
    # Catch-all: React SPA handles its own routing
    re_path(r'^(?!api/|admin/|static/|media/).*$', SPAView.as_view(), name='spa'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
