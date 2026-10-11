// Complete InDesign ExtendScript for Standard 5-Column Tabloid
#target indesign

function buildNewspaper() {
    var doc = app.documents.add();
    doc.viewPreferences.horizontalMeasurementUnits = MeasurementUnits.MILLIMETERS;
    doc.viewPreferences.verticalMeasurementUnits = MeasurementUnits.MILLIMETERS;
    
    with(doc.documentPreferences) {
        pageWidth = 280;
        pageHeight = 430;
        facingPages = true;
        pagesPerDocument = 2;
    }
    
    // Configure Margin and Columns
    for (var i = 0; i < doc.pages.length; i++) {
        with(doc.pages[i].marginPreferences) {
            top = 15;
            bottom = 15;
            left = 15;
            right = 15;
            columnCount = 5;
            columnGutter = 4;
        }
    }
    
    alert("Newspaper template generated successfully!");
}

buildNewspaper();
