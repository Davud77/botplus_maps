import React from 'react';

const PanoLayer = ({ togglePanoLayer }) => {
  return (
    <button className="layers-button" onClick={togglePanoLayer} style={{ position: 'absolute', top: '145px', right: '14px', zIndex: 1000 }}>
      <svg xmlns="http://www.w3.org/2000/svg" height="30px" viewBox="0 0 24 24" width="30px" fill="#fff">
        <path d="M0 0h24v24H0V0z" fill="none" />
        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 15c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"/>
      </svg>
    </button>
  );
};

export default PanoLayer;
