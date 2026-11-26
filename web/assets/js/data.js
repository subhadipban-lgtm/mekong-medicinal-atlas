/* Data tab: filterable catalog and dictionary tables. */
(function () {
  'use strict';
  document.addEventListener('DOMContentLoaded', function () {
    const dict = document.getElementById('dictTable');
    if (dict && window.DataTable) {
      new DataTable(dict, {
        paging: true, pageLength: 50, lengthMenu: [25, 50, 100, 250],
        order: [[0, 'asc'], [1, 'asc']], searching: true,
        language: { search: 'Filter:', searchPlaceholder: 'dataset or field name' }
      });
    }
    const cat = document.getElementById('catalogTable');
    if (cat && window.DataTable) {
      new DataTable(cat, {
        paging: false, searching: true, info: false,
        language: { search: 'Filter:', searchPlaceholder: 'dataset name' }
      });
    }
  });
})();
