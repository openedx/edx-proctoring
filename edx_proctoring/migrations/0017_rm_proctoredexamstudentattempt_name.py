# Generated by Django 2.2.24 on 2021-07-21 19:43

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('edx_proctoring', '0016_nullable_proctoredexamstudentattempt_name'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='proctoredexamstudentattempt',
            name='student_name',
        ),
        migrations.RemoveField(
            model_name='proctoredexamstudentattempthistory',
            name='student_name',
        ),
    ]
