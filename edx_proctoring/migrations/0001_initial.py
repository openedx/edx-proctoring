# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'ProctoredExam'
        db.create_table('proctoring_proctoredexam', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('created', self.gf('model_utils.fields.AutoCreatedField')(default=datetime.datetime.now)),
            ('modified', self.gf('model_utils.fields.AutoLastModifiedField')(default=datetime.datetime.now)),
            ('course_id', self.gf('django.db.models.fields.CharField')(max_length=255, db_index=True)),
            ('content_id', self.gf('django.db.models.fields.CharField')(max_length=255, db_index=True)),
            ('external_id', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, db_index=True)),
            ('exam_name', self.gf('django.db.models.fields.TextField')()),
            ('time_limit_mins', self.gf('django.db.models.fields.IntegerField')()),
            ('is_proctored', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('is_active', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal('edx_proctoring', ['ProctoredExam'])

        # Adding unique constraint on 'ProctoredExam', fields ['course_id', 'content_id']
        db.create_unique('proctoring_proctoredexam', ['course_id', 'content_id'])

        # Adding model 'ProctoredExamStudentAttempt'
        db.create_table('proctoring_proctoredexamstudentattempt', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('created', self.gf('model_utils.fields.AutoCreatedField')(default=datetime.datetime.now)),
            ('modified', self.gf('model_utils.fields.AutoLastModifiedField')(default=datetime.datetime.now)),
            ('user_id', self.gf('django.db.models.fields.IntegerField')(db_index=True)),
            ('proctored_exam', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['edx_proctoring.ProctoredExam'])),
            ('started_at', self.gf('django.db.models.fields.DateTimeField')(null=True)),
            ('completed_at', self.gf('django.db.models.fields.DateTimeField')(null=True)),
            ('external_id', self.gf('django.db.models.fields.CharField')(max_length=255, null=True, db_index=True)),
            ('status', self.gf('django.db.models.fields.CharField')(max_length=64)),
        ))
        db.send_create_signal('edx_proctoring', ['ProctoredExamStudentAttempt'])

        # Adding model 'ProctoredExamStudentAllowance'
        db.create_table('proctoring_proctoredexamstudentallowance', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('created', self.gf('model_utils.fields.AutoCreatedField')(default=datetime.datetime.now)),
            ('modified', self.gf('model_utils.fields.AutoLastModifiedField')(default=datetime.datetime.now)),
            ('user_id', self.gf('django.db.models.fields.IntegerField')()),
            ('proctored_exam', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['edx_proctoring.ProctoredExam'])),
            ('key', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('value', self.gf('django.db.models.fields.CharField')(max_length=255)),
        ))
        db.send_create_signal('edx_proctoring', ['ProctoredExamStudentAllowance'])

        # Adding unique constraint on 'ProctoredExamStudentAllowance', fields ['user_id', 'proctored_exam', 'key']
        db.create_unique('proctoring_proctoredexamstudentallowance', ['user_id', 'proctored_exam_id', 'key'])

        # Adding model 'ProctoredExamStudentAllowanceHistory'
        db.create_table('proctoring_proctoredexamstudentallowancehistory', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('created', self.gf('model_utils.fields.AutoCreatedField')(default=datetime.datetime.now)),
            ('modified', self.gf('model_utils.fields.AutoLastModifiedField')(default=datetime.datetime.now)),
            ('allowance_id', self.gf('django.db.models.fields.IntegerField')()),
            ('user_id', self.gf('django.db.models.fields.IntegerField')()),
            ('proctored_exam', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['edx_proctoring.ProctoredExam'])),
            ('key', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('value', self.gf('django.db.models.fields.CharField')(max_length=255)),
        ))
        db.send_create_signal('edx_proctoring', ['ProctoredExamStudentAllowanceHistory'])


    def backwards(self, orm):
        # Removing unique constraint on 'ProctoredExamStudentAllowance', fields ['user_id', 'proctored_exam', 'key']
        db.delete_unique('proctoring_proctoredexamstudentallowance', ['user_id', 'proctored_exam_id', 'key'])

        # Removing unique constraint on 'ProctoredExam', fields ['course_id', 'content_id']
        db.delete_unique('proctoring_proctoredexam', ['course_id', 'content_id'])

        # Deleting model 'ProctoredExam'
        db.delete_table('proctoring_proctoredexam')

        # Deleting model 'ProctoredExamStudentAttempt'
        db.delete_table('proctoring_proctoredexamstudentattempt')

        # Deleting model 'ProctoredExamStudentAllowance'
        db.delete_table('proctoring_proctoredexamstudentallowance')

        # Deleting model 'ProctoredExamStudentAllowanceHistory'
        db.delete_table('proctoring_proctoredexamstudentallowancehistory')


    models = {
        'edx_proctoring.proctoredexam': {
            'Meta': {'unique_together': "(('course_id', 'content_id'),)", 'object_name': 'ProctoredExam', 'db_table': "'proctoring_proctoredexam'"},
            'content_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'course_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'created': ('model_utils.fields.AutoCreatedField', [], {'default': 'datetime.datetime.now'}),
            'exam_name': ('django.db.models.fields.TextField', [], {}),
            'external_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_proctored': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'modified': ('model_utils.fields.AutoLastModifiedField', [], {'default': 'datetime.datetime.now'}),
            'time_limit_mins': ('django.db.models.fields.IntegerField', [], {})
        },
        'edx_proctoring.proctoredexamstudentallowance': {
            'Meta': {'unique_together': "(('user_id', 'proctored_exam', 'key'),)", 'object_name': 'ProctoredExamStudentAllowance', 'db_table': "'proctoring_proctoredexamstudentallowance'"},
            'created': ('model_utils.fields.AutoCreatedField', [], {'default': 'datetime.datetime.now'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'key': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'modified': ('model_utils.fields.AutoLastModifiedField', [], {'default': 'datetime.datetime.now'}),
            'proctored_exam': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['edx_proctoring.ProctoredExam']"}),
            'user_id': ('django.db.models.fields.IntegerField', [], {}),
            'value': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        },
        'edx_proctoring.proctoredexamstudentallowancehistory': {
            'Meta': {'object_name': 'ProctoredExamStudentAllowanceHistory', 'db_table': "'proctoring_proctoredexamstudentallowancehistory'"},
            'allowance_id': ('django.db.models.fields.IntegerField', [], {}),
            'created': ('model_utils.fields.AutoCreatedField', [], {'default': 'datetime.datetime.now'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'key': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'modified': ('model_utils.fields.AutoLastModifiedField', [], {'default': 'datetime.datetime.now'}),
            'proctored_exam': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['edx_proctoring.ProctoredExam']"}),
            'user_id': ('django.db.models.fields.IntegerField', [], {}),
            'value': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        },
        'edx_proctoring.proctoredexamstudentattempt': {
            'Meta': {'object_name': 'ProctoredExamStudentAttempt', 'db_table': "'proctoring_proctoredexamstudentattempt'"},
            'completed_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True'}),
            'created': ('model_utils.fields.AutoCreatedField', [], {'default': 'datetime.datetime.now'}),
            'external_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'modified': ('model_utils.fields.AutoLastModifiedField', [], {'default': 'datetime.datetime.now'}),
            'proctored_exam': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['edx_proctoring.ProctoredExam']"}),
            'started_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True'}),
            'status': ('django.db.models.fields.CharField', [], {'max_length': '64'}),
            'user_id': ('django.db.models.fields.IntegerField', [], {'db_index': 'True'})
        }
    }

    complete_apps = ['edx_proctoring']