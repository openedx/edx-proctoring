# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('edx_proctoring', '0002_proctoredexamstudentattempt_is_status_acknowledged'),
    ]

    operations = [
        migrations.AlterField(
            model_name='proctoredexamstudentattempt',
            name='is_sample_attempt',
            field=models.BooleanField(default=False, verbose_name='Is Sample Attempt'),
        ),
        migrations.AlterField(
            model_name='proctoredexamstudentattempt',
            name='taking_as_proctored',
            field=models.BooleanField(default=False, verbose_name='Taking as Proctored'),
        ),
    ]
