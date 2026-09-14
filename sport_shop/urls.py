from django.contrib import admin
from django.urls import path , include
from . import settings
from django.conf.urls.static import static
from .error_views import custom_bad_request, custom_page_not_found, custom_permission_denied, custom_server_error
from .media_views import ResilientMediaView

urlpatterns = [
    path('api/v1/', include('api.urls')),
    path('Mpannel/', admin.site.urls),
    path('i18n/', include('django.conf.urls.i18n')),
    path('media-files/<path:path>', ResilientMediaView.as_view(), name='resilient-media'),
    path('', include('home.urls')),
    path('accounts/', include('account.urls')),
    path('cart/', include('cart.urls')),

]
urlpatterns += static(settings.MEDIA_URL, document_root = settings.MEDIA_ROOT)

handler404 = custom_page_not_found
handler400 = custom_bad_request
handler403 = custom_permission_denied
handler500 = custom_server_error
