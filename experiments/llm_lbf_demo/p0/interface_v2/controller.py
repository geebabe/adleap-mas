"""One field-grounding clarification; the v1 adapter is preserved byte-for-byte."""
from ...e1.controller import SYSTEM as ORIGINAL_SYSTEM,payload as original_payload

VERSION='p0-capacity-grounding-2'
CLARIFICATION=(' Numeric field meanings: state.agents[].level is that robot\'s lifting '
    'capacity, and state.tasks[].level is that box\'s required lifting weight. For every '
    'selected box, sum the level values of only the robots assigned to that same box. '
    'This sum must be greater than or equal to the box\'s level. Robots assigned '
    'elsewhere or unassigned contribute nothing to that box. These physical rules '
    'apply under every supplied policy.')
SYSTEM=ORIGINAL_SYSTEM+CLARIFICATION


def payload(state,policy_text):
    request=original_payload(state,policy_text)
    request['messages'][0]['content']=SYSTEM
    return request
