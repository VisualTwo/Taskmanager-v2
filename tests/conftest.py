import builtins
from utils.rrule_helpers import compute_next_yearly_from, next_or_display_occurrence

# inject helpers into builtins so legacy-style tests that call them directly work
builtins.compute_next_yearly_from = compute_next_yearly_from
builtins.next_or_display_occurrence = next_or_display_occurrence
