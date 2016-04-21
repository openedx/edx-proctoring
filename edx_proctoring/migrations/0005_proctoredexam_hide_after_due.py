# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('edx_proctoring', '0004_auto_20160201_0523'),
    ]

    operations = [
        migrations.AddField(
            model_name='proctoredexam',
            name='hide_after_due',
            field=models.BooleanField(default=False),
        ),
    ]
