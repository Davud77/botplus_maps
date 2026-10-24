export interface OperationLog {at:string;service:string;message:string;level:string;}
const key='botplus_operation_logs';
export function readOperationLogs():OperationLog[]{
  try{return JSON.parse(sessionStorage.getItem(key)||'[]');}catch{return [];}
}
export function addOperationLog(message:string,level='info',service='Ортофотопланы'){
  try{sessionStorage.setItem(key,JSON.stringify([...readOperationLogs(),{at:new Date().toISOString(),service,message,level}].slice(-1000)));}catch{}
  window.dispatchEvent(new Event('operation-log'));
}
