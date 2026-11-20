import {ROOM_STATES,FREEZE_STATES,RELOCATION_STATES} from '../../constants/enums.js';
import {esc} from '../../utils/html.js';
export const roomBadge=value=>`<span class="badge room-${esc(value)}">${esc(ROOM_STATES[value]||value)}</span>`;
export const freezeBadge=value=>`<span class="badge fz-${esc(value)}">${esc(FREEZE_STATES[value]||value)}</span>`;
export const relocationBadge=value=>`<span class="badge rl-${esc(value)}">${esc(RELOCATION_STATES[value]||value)}</span>`;
