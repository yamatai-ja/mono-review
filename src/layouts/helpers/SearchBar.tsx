import React from "react";

const SearchBar = ({ searchList }: { searchList: any }) => {
  return (
    <div className="bg-theme-light p-8 text-center dark:bg-darkmode-theme-light">
      <h2 className="text-2xl font-bold mb-4">Search Bar Test</h2>
      <p>Search list items: {searchList?.length || 0}</p>
    </div>
  );
};

export default SearchBar;
