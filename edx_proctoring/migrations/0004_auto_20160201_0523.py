# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('edx_proctoring', '0003_auto_20160101_0525'),
    ]

    operations = [
        migrations.AlterField(
            model_name='proctoredexamsoftwaresecurereview',
            name='attempt_code',
            field=models.CharField(unique=True, max_length=255, db_index=True),
        ),
    ]
