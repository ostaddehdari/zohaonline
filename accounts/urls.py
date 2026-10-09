from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
urlpatterns=[
 path('login/',auth_views.LoginView.as_view(template_name='accounts/login.html'),name='login'),
 path('logout/',auth_views.LogoutView.as_view(),name='logout'),
 path('signup/',views.signup,name='signup'),
 path('manage/',views.user_list,name='user_list'),
 path('manage/new/',views.user_create,name='user_create'),
 path('manage/<int:pk>/edit/',views.user_edit,name='user_edit'),
 path('teams/',views.team_list,name='team_list'),
 path('teams/new/',views.team_create,name='team_create'),
 path('teams/<int:pk>/edit/',views.team_edit,name='team_edit'),
]
