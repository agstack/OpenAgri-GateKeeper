function getChartColorsArray(r) {
    var r = $(r).attr("data-colors");
    return (r = JSON.parse(r)).map(function(r) {
        r = r.replace(" ", "");
        if (-1 == r.indexOf("--")) return r;
        r = getComputedStyle(document.documentElement).getPropertyValue(r);
        return r || void 0
    })
}

let barchartColors = getChartColorsArray("#mini-chart1"),
    options = {
        series: [60, 40],
        chart: {
            type: "donut",
            height: 110
        },
        colors: barchartColors,
        legend: {
            show: !1
        },
        dataLabels: {
            enabled: !1
        }
    },
    chart = new ApexCharts(document.querySelector("#mini-chart1"), options);
chart.render();
options = {
    series: [30, 55],
    chart: {
        type: "donut",
        height: 110
    },
    colors: barchartColors = getChartColorsArray("#mini-chart2"),
    legend: {
        show: !1
    },
    dataLabels: {
        enabled: !1
    }
};
(chart = new ApexCharts(document.querySelector("#mini-chart2"), options)).render();
options = {
    series: [65, 45],
    chart: {
        type: "donut",
        height: 110
    },
    colors: barchartColors = getChartColorsArray("#mini-chart3"),
    legend: {
        show: !1
    },
    dataLabels: {
        enabled: !1
    }
};
(chart = new ApexCharts(document.querySelector("#mini-chart3"), options)).render();
options = {
    series: [30, 70],
    chart: {
        type: "donut",
        height: 110
    },
    colors: barchartColors = getChartColorsArray("#mini-chart4"),
    legend: {
        show: !1
    },
    dataLabels: {
        enabled: !1
    }
};
(chart = new ApexCharts(document.querySelector("#mini-chart4"), options)).render();