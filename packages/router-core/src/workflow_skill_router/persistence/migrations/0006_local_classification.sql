ALTER TABLE local_control_plans
ADD COLUMN classification_source TEXT NOT NULL DEFAULT 'legacy-replay';
ALTER TABLE local_control_plans
ADD COLUMN classification_confidence TEXT NOT NULL DEFAULT 'low';
ALTER TABLE local_control_plans
ADD COLUMN classifier_revision TEXT NOT NULL DEFAULT 'pre-beta.4';
ALTER TABLE local_control_plans
ADD COLUMN classification_reason_codes_json TEXT NOT NULL DEFAULT '[]';
