import {table} from '../components/common/table.js';
import {roomBadge,freezeBadge,relocationBadge} from '../components/common/status-badge.js';
import {esc,date} from '../utils/html.js';
import {session} from '../hooks/session.js';
const readonly=()=>session.user.role==='viewer'?'disabled':'';

export function custodyPage(rooms,orders,relocations,samples){
  const locOfId=id=>samples.find(s=>s.id===id)?.location ?? '—';
  const roomRows=rooms.map(r=>[
    `<strong>${esc(r.location)}</strong>${r.active_freeze?`<small>${esc(r.active_freeze.code)} · ${esc(r.active_freeze.reason||'')}</small>`:'<small>无生效封存</small>'}`,
    roomBadge(r.state),
    r.active_freeze?freezeBadge(r.active_freeze.status):'—',
    r.moving_relocation_id?`在途单 #${r.moving_relocation_id}`:'无在途',
    r.active_freeze
      ? (r.state==='sealed'
          ? `<button class="mini" data-release="${r.active_freeze.id}" ${readonly()}>解封</button>`
          : '<span class="muted">等待在途写完</span>')
      : `<button class="mini" data-freeze="${esc(r.location)}" ${readonly()}>发起停写</button>`
  ]);
  const orderRows=orders.slice(0,12).map(o=>[
    `<strong>${esc(o.code)}</strong><small>${esc(roomLoc(rooms,o.room_id))}</small>`,
    freezeBadge(o.status),esc(o.reason),esc(o.actor),date(o.created_at)
  ]);
  const relRows=relocations.slice(0,12).map(x=>[
    `<strong>${esc(x.code)}</strong><small>${esc(x.actor)}</small>`,
    esc(locOfId(x.sample_id)),`→ ${esc(roomLoc(rooms,x.target_room_id))}`,
    `${x.quantity} 份`,relocationBadge(x.status),
    x.status==='moving'?`<button class="mini" data-resume="${x.id}" ${readonly()}>恢复落账</button>`:date(x.posted_at)
  ]);
  return `<div class="split">
  <section>
    <div class="section-top"><h2>保管间封存状态</h2><span>WRITE FREEZE / SEAL</span></div>
    ${table(['保管间 / 封存单','房间状态','封存单','在途移位','操作'],roomRows)}
    <div class="notice">停写发起后该间不再受理新样本登记、改量、进出移位与移交；已受理的在途写入办完才显示「已封」。其他房间照常办理，历史单据始终可查。</div>
    <div class="section-top" style="margin-top:26px"><h2>封存单台账</h2><span>${orders.length} 单</span></div>
    ${table(['封存单 / 房间','状态','原因','发起人','时间'],orderRows)}
    <div class="section-top" style="margin-top:26px"><h2>跨间移位记录</h2><span>${relocations.length} 笔</span></div>
    ${table(['移位单 / 发起人','源间','目标间','数量','状态','落账/操作'],relRows)}
  </section>
  <section class="form-panel">
    <span class="eyebrow">CROSS-ROOM MOVE</span><h2>发起跨间移位</h2>
    <form id="relocation-form">
      <label>移位单编号<input name="code" placeholder="shift-20261120-01" required></label>
      <label>源样本批次<select name="sample_id">${samples.map(s=>`<option value="${s.id}">${esc(s.code)} · ${s.quantity} 份 · ${esc(s.location)}</option>`).join('')}</select></label>
      <label>目标保管间<input name="target_location" placeholder="冷藏间 A-07" list="room-list" required>
        <datalist id="room-list">${rooms.map(r=>`<option value="${esc(r.location)}"></option>`).join('')}</datalist></label>
      <div class="fields">
        <label>移位份数<input name="quantity" type="number" min="1" value="10" required></label>
        <label>保持在途（演练）<select name="hold"><option value="false">立即落账</option><option value="true">受理后保持在途</option></select></label>
      </div>
      <label>备注<input name="note" value="换柜移位"></label>
      <button class="primary" ${readonly()}>受理跨间移位 ↗</button>
    </form>
    <p class="help">源、目标两间都正常才受理，整笔落账；任一间已停写则整笔拒绝、不落任何账。「保持在途」用于演练在途时停写与重启恢复。</p>
    <span class="eyebrow" style="margin-top:24px">FREEZE / RELEASE</span><h2>按保管间停写</h2>
    <form id="freeze-form">
      <label>保管间位置<input name="location" list="room-list2" placeholder="冷藏间 A-03" required>
        <datalist id="room-list2">${rooms.map(r=>`<option value="${esc(r.location)}"></option>`).join('')}</datalist></label>
      <label>停写原因<input name="reason" value="换柜停写"></label>
      <button class="primary" ${readonly()}>发起停写 / 封存</button>
    </form>
    <p class="help">解封请在左侧封存列表对「已封」房间点解封；重发同一解封幂等不重复生效，旧封存单不能解开后来的新封存。</p>
  </section></div>`;
}
function roomLoc(rooms,id){const r=rooms.find(x=>x.id===id);return r?r.location:'—';}
