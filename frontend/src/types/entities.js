/** Sample:{id,code,title,quantity,location}; Transfer:{id,code,sample_id,destination,quantity,note}; Trial:{id,name,transfer_id,timeout_ms,status,result,error}
 *  Room:{id,location,state,active_freeze,moving_relocation_id}; FreezeOrder:{id,room_id,code,status,reason,actor,sealed_at,released_at}
 *  Relocation:{id,code,sample_id,source_room_id,target_room_id,quantity,status,note,actor,posted_at,result} */
export const entityNames=['samples','transfers','trials','rooms','freeze_orders','relocations'];
