# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('edx_proctoring', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='proctoredexamstudentattempt',
            name='is_status_acknowledged',
            field=models.BooleanField(default=False),
        ),
    ]
