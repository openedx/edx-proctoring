# -*- coding: utf-8 -*-


from django.contrib.auth import get_user_model
from django.db import models


class Profile(models.Model):
    """
    .. no_pii: Mock profile
    """
    user = models.OneToOneField(get_user_model(), on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
