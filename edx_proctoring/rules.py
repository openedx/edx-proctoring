"""Django Rules for edx_proctoring"""

import rules


@rules.predicate
def is_in_reviewer_group(user, attempt):
    """
    Returns whether user is in a group allowed to review this attempt
    """
    backend_group = f"{attempt['proctored_exam']['backend']}_review"
    return user.groups.filter(name=backend_group).exists()


rules.add_perm('edx_proctoring.can_review_attempt', is_in_reviewer_group | rules.is_staff)
