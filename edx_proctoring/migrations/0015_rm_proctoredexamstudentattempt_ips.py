# Generated by Django 2.2.24 on 2021-07-20 16:05

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('edx_proctoring', '0014_add_is_resumable_to_proctoredexamstudentattempt'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='proctoredexamstudentattempt',
            name='last_poll_ipaddr',
        ),
        migrations.RemoveField(
            model_name='proctoredexamstudentattempt',
            name='last_poll_timestamp',
        ),
        migrations.RemoveField(
            model_name='proctoredexamstudentattempthistory',
            name='last_poll_ipaddr',
        ),
        migrations.RemoveField(
            model_name='proctoredexamstudentattempthistory',
            name='last_poll_timestamp',
        ),
    ]
