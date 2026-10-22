// Run with the installed MuPDF mutool. PDF destinations are zero based.
var document = Document.openDocument(scriptArgs[0]);
function entries(rows) {
    return rows.map(function (row) {
        var destination = document.resolveLink(row.uri);
        var page = typeof destination === "number" ? destination : destination.page;
        var result = {title: row.title, uri: row.uri, pdfPage: page + 1};
        if (row.down) result.children = entries(row.down);
        return result;
    });
}
print(JSON.stringify({pages: document.countPages(), outline: entries(document.loadOutline())}));
