"""A playful "human effort" equivalent for tracked GPU energy.

Converts an amount of electrical energy (Wh) into an equivalent number
of minutes on a rowing machine, based on typical calorie expenditure
for moderate-effort rowing.

This is illustrative, not scientifically rigorous: human calorie burn
varies a lot with body weight, intensity, and fitness level. Reference
figure: ~260 kcal / 30 min of moderate-effort rowing for a ~70 kg
(155 lb) adult (Harvard Health Publishing calorie-burn tables), i.e.
about 8.7 kcal/min. Using 1 kcal = 1.163 Wh (thermochemical calorie),
that's roughly 10.1 Wh of human metabolic energy per minute of rowing.
"""

KCAL_PER_MIN_ROWING = 260 / 30  # moderate effort, ~70 kg / 155 lb adult
WH_PER_KCAL = 1.163
WH_PER_MIN_ROWING = KCAL_PER_MIN_ROWING * WH_PER_KCAL  # ~10.1 Wh/min


def rowing_minutes_equivalent(energy_wh: float) -> float:
    """Minutes of moderate-effort rowing burning about as much energy (Wh)."""
    return energy_wh / WH_PER_MIN_ROWING


def format_rowing_equivalent(energy_wh: float) -> str:
    """Human-readable rowing-machine equivalent for an energy amount (Wh)."""
    minutes = rowing_minutes_equivalent(energy_wh)
    if minutes < 1:
        return f"🚣 {minutes * 60:.0f} sec of rowing"
    if minutes < 60:
        return f"🚣 {minutes:.1f} min of rowing"
    return f"🚣 {minutes / 60:.1f} h of rowing"
