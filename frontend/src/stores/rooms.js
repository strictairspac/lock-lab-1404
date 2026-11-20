import {roomsApi} from '../api/rooms.js';
export const roomsStore={items:[],async refresh(){this.items=await roomsApi.list();return this.items;}};
