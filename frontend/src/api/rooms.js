import {api} from './client.js';
export const roomsApi={
  list:()=>api('/rooms'),
  freeze:(location,reason)=>api('/rooms/freeze','POST',{location,reason}),
  release:(order_id)=>api('/rooms/release','POST',{order_id}),
  orders:()=>api('/freeze-orders')
};
