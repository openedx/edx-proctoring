# Generated by Django 2.2.24 on 2021-07-20 18:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('edx_proctoring', '0015_rm_proctoredexamstudentattempt_ips'),
    ]

    operations = [
        migrations.AlterField(
            model_name='proctoredexamstudentattempt',
            name='student_name',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='proctoredexamstudentattempthistory',
            name='student_name',
            field=models.CharField(max_length=255, null=True),
        ),
    ]
