const appState = {
    currentStep: 1,
    inputData: {
        seatingStyle: null, // 'banquet', 'cabaret', 'theatre' etc.
        numSeatsPerTable: 0,
        headSeat: null,
        footSeat: null,
        numTables: 1,
        guestInfo: null,
        scoreEstimator: null
    }
}

const elements = {
    steps: document.querySelectorAll('.step-section'),
    nextBtn: document.getElementById('next-btn'),
    prevBtn: document.getElementById('prev-btn'),
    progressFill: document.getElementById('progress-fill'),
    circle1: document.getElementById('circle-1'),
    circle2: document.getElementById('circle-2'),
    circle3: document.getElementById('circle-3'),
    visualContainer: document.getElementById('visual-container'),
    inputBox: document.getElementById('input-box')
}

function validateInput(tableOptions=['banquet','cabaret','theatre'],
                        maxNumTables=10,
                        maxNumSeats=100){
     

}
function updateUI(){
    elements.steps.classList.add("hidden")
}
function drawBanquetTable(containerId,numTables=1,numSeatsPerTable=7,headSeat=true,footSeat=false,
    wrapperWidth=192,wrapperHeight=192){
    const canvas = document.getElementById(containerId);
    canvas.innerHTML = '';
    canvas.className = "relative h-full w-full flex flex-wrap justify-center items-center gap-8 p-4";

    for(let i = 0; i < numTables; i++){
        const tableWrapper = document.createElement('div');
        tableWrapper.style.width = `${wrapperWidth}px`;
        tableWrapper.style.height = `${wrapperHeight}px`;
        tableWrapper.className = 'relative flex-shrink-0 overflow-visible group';
        console.log("Wrapper Dimension:",tableWrapper.style.width,tableWrapper.style.height);
        canvas.appendChild(tableWrapper);

        const table = document.createElement('div');
        table.className = `table-banquet bg-slate-500 group-hover:bg-brand-dark`;
        tableWrapper.appendChild(table);
        const tableWidth = 0.4 * wrapperWidth;
        const tableHeight = 0.8 * wrapperHeight;
        table.style.width = `${tableWidth}px`;
        table.style.height = `${tableHeight}px`;
        const tableTopPos = 0.5*(wrapperHeight-tableHeight);
        const tableLeftPos = 0.5*(wrapperWidth-tableWidth);
        console.log("Table Dimensions:", table.style.width, table.style.height);

        let headPlaced = false;
        let footPlaced = false;
        
        for(let j = 0; j < numSeatsPerTable; j++){
            const seat = document.createElement('div');
            seat.className = 'seat bg-slate-700 group-hover:!bg-brand-dark';
            const sideSeatCount = (numSeatsPerTable - Number(headSeat) - Number(footSeat))/2; //per side
            const seatWidth =  (tableHeight/sideSeatCount) * 0.8;
            const seatHeight = 1.2*seatWidth;
            const seatNumber = j-Number(headSeat)-Number(footSeat);
            seat.style.width = `${seatWidth}px`;
            seat.style.height = `${seatHeight}px`;
            console.log("Seat dimensions: ", seat.style.width,seat.style.height);

            if(headSeat && !headPlaced){
                seat.style.top = `${tableTopPos - 1.1*seatHeight}px`;
                seat.style.left = `${tableLeftPos+0.5*(tableWidth-seatWidth)}px`;
                headPlaced = true;
            }
            else if(footSeat && !footPlaced){
                seat.style.top = `${tableTopPos + tableHeight + 0.1*seatHeight}px`;
                seat.style.left = `${tableLeftPos+0.5*(tableWidth-seatWidth)}px`;
                seat.style.transform = 'rotate(180deg)';
                footPlaced = true;
            }
            else{
                const seatCentroidY = tableTopPos + (0.5 + Math.floor(seatNumber/2))*(tableHeight/sideSeatCount);
                if(seatNumber%2 == 0){
                    //Left Side
                    seat.style.left = `${tableLeftPos - 0.6*seatHeight-0.5*seatWidth}px`;
                    seat.style.top = `${seatCentroidY - 0.5*seatHeight}px`;
                    seat.style.transform = 'rotate(-90deg)';
                }else{
                    //Right Side
                    seat.style.left = `${tableLeftPos+tableWidth+0.6*seatHeight-0.5*seatWidth}px`;
                    seat.style.top = `${seatCentroidY - 0.5*seatHeight}px`;
                    seat.style.transform = 'rotate(90deg)';
                }
    
            }
            tableWrapper.appendChild(seat);
        }
    
    }
}

function drawCabaretTable(containerId,numTables=1,numSeatsPerTable=6,wrapperWidth=192,wrapperHeight=192){
    const canvas = document.getElementById(containerId);
    canvas.innerHTML = '';
    canvas.className = "relative h-full w-full flex flex-wrap justify-center items-center gap-8 p-4";
    
    for(let i = 0; i < numTables; i++){
        const tableWrapper = document.createElement('div');
        tableWrapper.style.width = `${wrapperWidth}px`;
        tableWrapper.style.height = `${wrapperHeight}px`;
        tableWrapper.className = 'relative flex-shrink-0 overflow-visible group';
        console.log("Wrapper Dimension:",tableWrapper.style.width,tableWrapper.style.height);
        canvas.appendChild(tableWrapper);

        const table = document.createElement('div');
        table.className = `table-cabaret bg-slate-500 group-hover:bg-brand-dark`;
        tableWrapper.appendChild(table);
        const tableWidth = 0.6 * wrapperWidth;
        const tableHeight = 0.6 * wrapperHeight;
        const r = tableWidth/2;
        table.style.width = `${tableWidth}px`;
        table.style.height = `${tableHeight}px`;
        const tableTopPos = 0.5*(wrapperHeight-tableHeight);
        const tableLeftPos = 0.5*(wrapperWidth-tableWidth);
        
        console.log("radius: ", r);

        for(let j = 0; j < numSeatsPerTable; j++){
            const seat = document.createElement('div');
            seat.className = 'seat bg-slate-700 group-hover:!bg-brand-dark';
            const seatWidth = (1.1*Math.PI*tableWidth)/(2*numSeatsPerTable);
            const seatHeight = 1.2*seatWidth;
            seat.style.width = `${seatWidth}px`;
            seat.style.height = `${seatHeight}px`;
            console.log("Seat dimensions: ", seat.style.width,seat.style.height);
            
            const Angle = j*Math.PI/(numSeatsPerTable-1);
            const Hypotenuse = 1.1*r + 0.5*seatHeight;
            const seatCentroidX = tableLeftPos + r - Math.cos(Angle)*Hypotenuse; //from the left
            const seatCentroidY = tableTopPos + r - Math.sin(Angle)*Hypotenuse; //from the top

            seat.style.left = `${seatCentroidX - 0.5*seatWidth}px`;
            seat.style.top = `${seatCentroidY - 0.5*seatHeight}px`;
            seat.style.transform = `rotate(${-1*Math.PI/2 + Angle}rad)`; 

            tableWrapper.appendChild(seat);
        }
    }
}

function drawTheatre(containerId,numRows=2,numSeatsPerRow=4,wrapperWidth=192){
    //"Table" == "Row"
    const canvas = document.getElementById(containerId);
    canvas.innerHTML = '';
    canvas.className = "relative h-full w-full flex flex-wrap justify-center items-center gap-8 p-4";
    const totalHeight = canvas.offsetHeight || 192;
    const padding = 16;
    const gap = (numRows - 1) * 8;
    const availableHeight = totalHeight - padding - gap;
    const wrapperHeight = 0.8*availableHeight / numRows;

    for(let i = 0; i<numRows; i++){
        const rowWrapper = document.createElement('div');
        rowWrapper.style.width = `${wrapperWidth}px`;
        rowWrapper.style.height = `${wrapperHeight}px`;
        rowWrapper.className = 'relative flex-shrink-0 overflow-visible group';
        console.log("Wrapper Dimension:",rowWrapper.style.width,rowWrapper.style.height);
        canvas.appendChild(rowWrapper);
        for(let j=0; j<numSeatsPerRow; j++){
            const seat = document.createElement('div');
            seat.className = 'seat bg-slate-700 group-hover:!bg-brand-dark';
            const seatWidth = 0.9*wrapperWidth/numSeatsPerRow;
            const seatHeight = 0.8*wrapperHeight;
            seat.style.width = `${seatWidth}px`;
            seat.style.height = `${seatHeight}px`;

            seat.style.left = `${j*(wrapperWidth/numSeatsPerRow)}px`;
            //seat.style.top = `${0.5*seatHeight}px`;
            rowWrapper.appendChild(seat);
        }
    }
}

// Function to render the "Preview" versions in Step 1
function renderPreviews() {
    drawBanquetTable('viz-banquet');
    drawCabaretTable('viz-cabaret');
    drawTheatre('viz-theatre');
}

function setupCheckboxLogic() {
    const headCheck = document.getElementById('check-head');
    const footCheck = document.getElementById('check-foot');
    const footLabel = document.getElementById('foot-label');

    headCheck.addEventListener('change', function() {
        if (this.checked) {
            footCheck.disabled = false;
            footLabel.classList.remove('cursor-not-allowed', 'opacity-50');
            footLabel.querySelector('span').classList.replace('text-slate-400', 'text-slate-600');
        } else {
            footCheck.checked = false;
            footCheck.disabled = true;
            footLabel.classList.add('cursor-not-allowed', 'opacity-50');
            footLabel.querySelector('span').classList.replace('text-slate-600', 'text-slate-400');
        }
    });
}

function setupCardListeners() {
    const cards = document.querySelectorAll('.style-card');
    
    cards.forEach(card => {
        card.addEventListener('click', function() {
            const vizDiv = this.querySelector('[id^="viz-"]');
            if (vizDiv) {
                const style = vizDiv.id.replace('viz-', '');
                selectStyle(style);
            }
        });
    });
}
function selectStyle(style) {
    console.log("Style Selected:", style);
    appState.inputData.seatingStyle = style;
    document.querySelectorAll('.style-card').forEach(card => {
        card.classList.remove('border-brand', 'ring-2', 'ring-brand/20');
        card.classList.add('border-slate-200');
        const label = card.querySelector('span');
        if (label) {
            label.classList.replace('text-brand-dark', 'text-slate-400');
        }
    });
    const currentCard = document.getElementById(`viz-${style}`).closest('.style-card');
    currentCard.classList.add('border-brand-dark', 'bg-brand-dark/5', 'ring-2', 'ring-brand-dark');

    const inputContainer = document.getElementById('setup-details');
    inputContainer.classList.remove('hidden');
    document.getElementById('chosen-style-name').innerText = style;
    document.getElementById('table-qty-label').innerText = (style=='theatre')? 'Number of Rows':'Number of Tables';
    document.getElementById('seat-qty-label').innerText = (style=='theatre')? 'Number of Seats per Row':'Number of Seats per Table';

    const extraOptions = document.getElementById('extra-options-container');
    const headCheck = document.getElementById('check-head');
    const footCheck = document.getElementById('check-foot');

    if (style === 'banquet') {
        extraOptions.classList.remove('hidden');
        headCheck.checked = false;
        footCheck.checked = false;
        footCheck.disabled = true; 
    } else {
        extraOptions.classList.add('hidden');
    }

    const configPanel = document.getElementById('setup-details');
    configPanel.classList.remove('hidden');
    inputContainer.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function init() {
    console.log("CommonTable App Initialized");
    renderPreviews(); // Set the initial step and progress
}

init();
document.addEventListener('DOMContentLoaded', ()=>{setupCheckboxLogic();setupCardListeners()});