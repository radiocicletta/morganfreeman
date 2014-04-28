(function($){

    var StatChart = function(element, options) {
        this.init(element, options);
    };

    StatChart.prototype = {
        constructor: StatChart,
        init: function(element, options){
            this.element = $(element);
            this.options = options;
            this.data = this.element.data();
            this.type = options.type || this.data.type;
            this.values = options.values;
            this.orientation = options.orientation || 'vertical';
            this.key = options.key || 'undefined';

            this.element.on(
                'stats:redraw',
                function(data){
                    this.draw();
                });

            this.draw = function(){
                var el = this.element[0];
                if (this.type === "line")
                    return stats.renderlinechart(
                        el,
                        this.values,
                        this.options.width,
                        this.options.height);
                if (this.type === "heatmap")
                    return stats.renderheatmap(
                        el,
                        this.values,
                        this.options.width,
                        this.options.height); 
                if (this.type === "bar")
                    return stats.renderbarchart(
                        el,
                        this.values,
                        this.options.width,
                        this.options.height,
                        this.key,
                        this.orientation); 

            };

            this.draw();
        },

        setValue: function(val){
            this.values = val;
            this.draw();
        }

    };

    $.fn.statchart = function(option, val){
        return this.each(function(){
            var $this = $(this),
                data = $this.data('statchart'),
                options = typeof option === 'object' && option;
            if (!data){
                $this.data('statchart', new StatChart(
                    this, $.extend({}, $.fn.statchart.defaults, options)));
            }
            if (typeof option === 'string') data[option](val);
        });
    };
    $.fn.statchart.Constructor = StatChart;
})($);

$(function(){

    var url = document.location.href,

        range = stats.range(),

        updaterange = function() {
            $.getJSON(url + 
                      "/mount/*/" + 
                      range.start.getTime() + "/" + 
                      range.stop.getTime(),
                function(data){
                    if (data === null)
                        return;
                    var unified = stats.util.ua_os(
                        stats.util.ua_players(
                        stats.util.unify(data)
                    ));
                    $('#linechrt-global').data('statchart').setValue(unified);
                    $('#dotchrt-global').data('statchart').setValue(unified);
                    $('#player-barchrt-global').data('statchart').setValue(unified);
                    $('#os-barchrt-global').data('statchart').setValue(unified);
                });
        };

    $("#input-rangestart").datetimepicker({
        language: 'it-IT',
        endDate: new Date()
    }).on('changeDate', function(e){ 
        range = stats.range(e.date);
        updaterange();
    })
    .data('datetimepicker').setLocalDate(range.start);

    $("#input-rangestop").datetimepicker({
        language: 'it-IT',
        endDate: new Date()
    }).on('changeDate', function(e){
        range = stats.range(range.start.getTime(), e.date);
        updaterange();
    })
    .data('datetimepicker').setLocalDate(range.stop);

    $('#linechrt-global').statchart({
            type: 'line',
            width: 640,
            height: 200
        });
    $('#dotchrt-global').statchart({
            type: 'heatmap',
            width: 640,
            height: 320 
        });
    $('#player-barchrt-global').statchart({
            type: 'bar',
            width: 640,
            height: 640,
            orientation: 'vertical',
            key: 'ua_browser'
        });

    $('#os-barchrt-global').statchart({
            type: 'bar',
            width: 640,
            height: 640,
            orientation: 'vertical',
            key: 'ua_os'
        });

    updaterange();
});
