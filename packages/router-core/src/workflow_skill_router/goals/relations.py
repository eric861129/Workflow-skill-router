from workflow_skill_router.routing.models import GoalRelation


SEMANTIC_MUTATION_ALLOWED = {GoalRelation.PROGRESS, GoalRelation.STEER}
CONTROL_QUERY_RELATIONS = {GoalRelation.STATUS}
DETACHED_RELATIONS = {GoalRelation.SIDE_QUESTION, GoalRelation.UNRELATED}

