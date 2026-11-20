import {api} from './client.js';
export const relocationsApi={
  list:()=>api('/relocations'),
  create:data=>api('/relocations','POST',data),
  resume:relocation_id=>api('/relocations/resume','POST',{relocation_id})
};
