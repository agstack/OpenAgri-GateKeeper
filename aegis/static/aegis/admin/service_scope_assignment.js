(function () {
  function findRow(fieldName) {
    return document.querySelector(
      ".form-row.field-" + fieldName + ", .field-" + fieldName
    );
  }

  function findInput(fieldName) {
    return document.getElementById("id_" + fieldName);
  }

  function setRowVisibility(fieldName, visible) {
    var row = findRow(fieldName);
    if (!row) {
      return;
    }
    row.style.display = visible ? "" : "none";
  }

  function syncScopeFields() {
    var scopeType = findInput("scope_type");
    if (!scopeType) {
      return;
    }
    var isFarm = scopeType.value === "farm";
    var isParcel = scopeType.value === "parcel";
    setRowVisibility("scope_farms", isFarm);
    setRowVisibility("scope_parcels", isParcel);
  }

  function init() {
    var scopeType = findInput("scope_type");
    syncScopeFields();
    if (scopeType) {
      scopeType.addEventListener("change", syncScopeFields);
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})();
