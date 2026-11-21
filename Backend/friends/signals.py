from django.dispatch import Signal

# Sent after a friendship is removed or the pair is blocked. kwargs: user_ids=(a_id, b_id)
friendship_removed = Signal()
