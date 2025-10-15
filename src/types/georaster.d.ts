declare module 'georaster' {
  const parseGeoraster: (buffer: ArrayBuffer) => Promise<any>;
  export default parseGeoraster;
}