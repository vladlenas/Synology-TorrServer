Ext.namespace("SYNO.SDS.TorrServer.Utils");

Ext.apply(SYNO.SDS.TorrServer.Utils, function() {
    return {
        getMainHtml: function() {
            return '<iframe src="webman/3rdparty/TorrServer/index.cgi?_ts=' +
                new Date().getTime() +
                '" title="TorrServer Helper" ' +
                'style="width:100%;height:100%;border:none;margin:0;padding:0;" ' +
                'frameborder="0"></iframe>';
        }
    }
}());

Ext.define("SYNO.SDS.TorrServer.Application", {
    extend: "SYNO.SDS.AppInstance",
    appWindowName: "SYNO.SDS.TorrServer.MainWindow",

    constructor: function() {
        this.callParent(arguments);
    }
});

Ext.define("SYNO.SDS.TorrServer.MainWindow", {
    extend: "SYNO.SDS.AppWindow",

    constructor: function(a) {
        var MY = SYNO.SDS.TorrServer;

        this.appInstance = a.appInstance;

        MY.MainWindow.superclass.constructor.call(this, Ext.apply({
            layout: "fit",
            resizable: true,
            cls: "syno-torrserver-win",
            maximizable: true,
            minimizable: true,
            width: 1100,
            height: 760,
            html: MY.Utils.getMainHtml()
        }, a));

        MY.Utils.ApplicationWindow = this;
    },

    onOpen: function() {
        SYNO.SDS.TorrServer.MainWindow.superclass.onOpen.apply(
            this,
            arguments
        );
    },

    onRequest: function(a) {
        SYNO.SDS.TorrServer.MainWindow.superclass.onRequest.call(
            this,
            a
        );
    },

    onClose: function() {
        clearTimeout(SYNO.SDS.TorrServer.TimeOutID);
        SYNO.SDS.TorrServer.TimeOutID = undefined;

        SYNO.SDS.TorrServer.MainWindow.superclass.onClose.apply(
            this,
            arguments
        );

        this.doClose();
        return true;
    }
});
