import {relocationsApi} from '../api/relocations.js';
export const relocationsStore={items:[],async refresh(){this.items=await relocationsApi.list();return this.items;}};
