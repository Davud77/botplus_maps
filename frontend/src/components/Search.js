import React, { useState } from 'react';

const Search = ({ handleSearch }) => {
  const [searchInput, setSearchInput] = useState('');
  const [expanded, setExpanded] = useState(false);

  const handleSearchChange = (event) => {
    setSearchInput(event.target.value);
  };

  const handleButtonClick = () => {
    if (expanded) {
      handleSearch(searchInput);
    } else {
      setExpanded(true);
    }
  };

  const handleBlur = () => {
    if (searchInput === '') {
      setExpanded(false);
    }
  };

  return (
    <div className={`search-container ${expanded ? 'expanded' : ''}`}>
      <input
        type="text"
        value={searchInput}
        onChange={handleSearchChange}
        placeholder="Координаты в формате 59.333189, 57.128906"
        className="search-input"
        onBlur={handleBlur}
        style={{ display: expanded ? 'block' : 'none' }}
      />
      <button onClick={handleButtonClick} className="search-button">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          height="30px"
          viewBox="0 0 24 24"
          width="30px"
          fill="#fff"
        >
          <path d="M0 0h24v24H0V0z" fill="none" />
          <path d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z" />
        </svg>
      </button>
    </div>
  );
};

export default Search;
