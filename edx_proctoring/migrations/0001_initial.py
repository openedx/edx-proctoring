# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'ProctoredExam'
        db.create_table('edx_proctoring_proctoredexam', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('course_id', self.gf('django.db.models.fields.CharField')(max_length=255, db_index=True)),
            ('content_id', self.gf('django.db.models.fields.CharField')(max_length=255, db_index=True)),
            ('external_id', self.gf('django.db.models.fields.TextField')(null=True, db_index=True)),
            ('time_limit_mins', self.gf('django.db.models.fields.IntegerField')()),
            ('is_proctored', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('is_active', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal('edx_proctoring', ['ProctoredExam'])

        # Adding model 'ProctoredExamStudentAttempt'
        db.create_table('edx_proctoring_proctoredexamstudentattempt', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('user_id', self.gf('django.db.models.fields.IntegerField')(db_index=True)),
            ('proctored_exam', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['edx_proctoring.ProctoredExam'])),
            ('started_at', self.gf('django.db.models.fields.DateTimeField')(null=True)),
            ('completed_at', self.gf('django.db.models.fields.DateTimeField')(null=True)),
            ('external_id', self.gf('django.db.models.fields.TextField')(null=True, db_index=True)),
        ))
        db.send_create_signal('edx_proctoring', ['ProctoredExamStudentAttempt'])

        # Adding model 'ProctoredExamStudentAllowance'
        db.create_table('edx_proctoring_proctoredexamstudentallowance', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('created', self.gf('model_utils.fields.AutoCreatedField')(default=datetime.datetime.now)),
            ('modified', self.gf('model_utils.fields.AutoLastModifiedField')(default=datetime.datetime.now)),
            ('user_id', self.gf('django.db.models.fields.IntegerField')()),
            ('proctored_exam', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['edx_proctoring.ProctoredExam'])),
            ('key', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('value', self.gf('django.db.models.fields.CharField')(max_length=255)),
        ))
        db.send_create_signal('edx_proctoring', ['ProctoredExamStudentAllowance'])

        # Adding model 'ProctoredExamStudentAllowanceHistory'
        db.create_table('edx_proctoring_proctoredexamstudentallowancehistory', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('created', self.gf('model_utils.fields.AutoCreatedField')(default=datetime.datetime.now)),
            ('modified', self.gf('model_utils.fields.AutoLastModifiedField')(default=datetime.datetime.now)),
            ('user_id', self.gf('django.db.models.fields.IntegerField')()),
            ('proctored_exam', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['edx_proctoring.ProctoredExam'])),
            ('key', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('value', self.gf('django.db.models.fields.CharField')(max_length=255)),
        ))
        db.send_create_signal('edx_proctoring', ['ProctoredExamStudentAllowanceHistory'])


    def backwards(self, orm):
        # Deleting model 'ProctoredExam'
        db.delete_table('edx_proctoring_proctoredexam')

        # Deleting model 'ProctoredExamStudentAttempt'
        db.delete_table('edx_proctoring_proctoredexamstudentattempt')

        # Deleting model 'ProctoredExamStudentAllowance'
        db.delete_table('edx_proctoring_proctoredexamstudentallowance')

        # Deleting model 'ProctoredExamStudentAllowanceHistory'
        db.delete_table('edx_proctoring_proctoredexamstudentallowancehistory')


    models = {
        'edx_proctoring.proctoredexam': {
            'Meta': {'object_name': 'ProctoredExam'},
            'content_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'course_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'external_id': ('django.db.models.fields.TextField', [], {'null': 'True', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_proctored': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'time_limit_mins': ('django.db.models.fields.IntegerField', [], {})
        },
        'edx_proctoring.proctoredexamstudentallowance': {
            'Meta': {'object_name': 'ProctoredExamStudentAllowance'},
            'created': ('model_utils.fields.AutoCreatedField', [], {'default': 'datetime.datetime.now'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'key': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'modified': ('model_utils.fields.AutoLastModifiedField', [], {'default': 'datetime.datetime.now'}),
            'proctored_exam': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['edx_proctoring.ProctoredExam']"}),
            'user_id': ('django.db.models.fields.IntegerField', [], {}),
            'value': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        },
        'edx_proctoring.proctoredexamstudentallowancehistory': {
            'Meta': {'object_name': 'ProctoredExamStudentAllowanceHistory'},
            'created': ('model_utils.fields.AutoCreatedField', [], {'default': 'datetime.datetime.now'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'key': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'modified': ('model_utils.fields.AutoLastModifiedField', [], {'default': 'datetime.datetime.now'}),
            'proctored_exam': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['edx_proctoring.ProctoredExam']"}),
            'user_id': ('django.db.models.fields.IntegerField', [], {}),
            'value': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        },
        'edx_proctoring.proctoredexamstudentattempt': {
            'Meta': {'object_name': 'ProctoredExamStudentAttempt'},
            'completed_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True'}),
            'external_id': ('django.db.models.fields.TextField', [], {'null': 'True', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'proctored_exam': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['edx_proctoring.ProctoredExam']"}),
            'started_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True'}),
            'user_id': ('django.db.models.fields.IntegerField', [], {'db_index': 'True'})
        }
    }

    complete_apps = ['edx_proctoring']