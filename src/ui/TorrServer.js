Ext.namespace("SYNO.SDS.TorrServer.Utils");

Ext.apply(SYNO.SDS.TorrServer.Utils, function () {
    return {
        getMainHtml: function () {
            // DSM Desktop is normally HTTPS. An HTTP iframe would be blocked
            // as mixed content, so use the helper HTTPS endpoint when DSM is
            // opened over HTTPS. Port 8095 remains available for direct HTTP.
            var protocol = window.location.protocol;
            var host = window.location.hostname;
            var port = (protocol === "https:") ? "8096" : "8095";
            var url = protocol + "//" + host + ":" + port + "/";

            // Timestamp prevents the helper page from being cached by the browser.
            return '<iframe src="' + url + '?_ts=' + new Date().getTime() + '" ' +
                'title="TorrServer Helper" ' +
                'style="width:100%;height:100%;border:0;margin:0;padding:0;display:block;" ' +
                'frameborder="0"></iframe>';
        }
    };
}());

Ext.define("SYNO.SDS.TorrServer.Application", {
    extend: "SYNO.SDS.AppInstance",
    appWindowName: "SYNO.SDS.TorrServer.MainWindow",

    constructor: function () {
        this.callParent(arguments);
    }
});

Ext.define("SYNO.SDS.TorrServer.MainWindow", {
    extend: "SYNO.SDS.AppWindow",

    constructor: function (cfg) {
        var MY = SYNO.SDS.TorrServer;

        this.appInstance = cfg && cfg.appInstance;

        MY.MainWindow.superclass.constructor.call(this, Ext.apply({
            layout: "fit",
            resizable: true,
            maximizable: true,
            minimizable: true,
            width: 1100,
            height: 760,
            minWidth: 800,
            minHeight: 550,
            title: "TorrServer MatriX",
            html: MY.Utils.getMainHtml()
        }, cfg));

        MY.Utils.ApplicationWindow = this;
    },

    onOpen: function () {
        SYNO.SDS.TorrServer.MainWindow.superclass.onOpen.apply(this, arguments);
    },

    onRequest: function (request) {
        SYNO.SDS.TorrServer.MainWindow.superclass.onRequest.call(this, request);
    },

    onClose: function () {
        SYNO.SDS.TorrServer.MainWindow.superclass.onClose.apply(this, arguments);
        this.doClose();
        return true;
    }
});
