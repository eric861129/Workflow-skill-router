ALTER TABLE local_control_plans
ADD COLUMN routing_domains_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE local_control_plans
ADD COLUMN routing_tags_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE local_control_plans
ADD COLUMN workspace_identity_digest TEXT;
ALTER TABLE local_control_plans
ADD COLUMN profile_objective_keywords_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE local_control_plans
ADD COLUMN profile_domains_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE local_control_plans
ADD COLUMN profile_tags_json TEXT NOT NULL DEFAULT '[]';
