ALTER TABLE local_control_plans ADD COLUMN route_source TEXT NOT NULL DEFAULT 'builtin-default';
ALTER TABLE local_control_plans ADD COLUMN routing_profile_ids_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE local_control_plans ADD COLUMN routing_profile_digest TEXT;
ALTER TABLE local_control_plans ADD COLUMN matched_profile_rule_id TEXT;
ALTER TABLE local_control_plans ADD COLUMN planned_skill_ids_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE local_control_plans ADD COLUMN planned_skill_tree_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE local_control_plans ADD COLUMN activation_status TEXT NOT NULL DEFAULT 'not-planned';
ALTER TABLE local_control_plans ADD COLUMN profile_warnings_json TEXT NOT NULL DEFAULT '[]';

UPDATE local_control_plans
SET route_source = CASE
        WHEN explicit_skill_ids_json <> '[]' THEN 'user-explicit'
        ELSE 'builtin-default'
    END,
    planned_skill_ids_json = explicit_skill_ids_json,
    activation_status = CASE
        WHEN explicit_skill_ids_json <> '[]' THEN 'intended-unverified'
        ELSE 'not-planned'
    END;
