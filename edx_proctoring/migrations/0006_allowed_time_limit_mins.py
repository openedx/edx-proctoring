# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('edx_proctoring', '0005_proctoredexam_hide_after_due'),
    ]

    operations = [
        migrations.AlterField(
            model_name='proctoredexamstudentattempt',
            name='allowed_time_limit_mins',
            field=models.IntegerField(null=True),
        ),
        migrations.AlterField(
            model_name='proctoredexamstudentattempthistory',
            name='allowed_time_limit_mins',
            field=models.IntegerField(null=True),
        ),
    ]
