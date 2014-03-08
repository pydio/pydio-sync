HEADERS       = window.h \
                Subscriber.hpp \
                SampleBase.hpp \
                ../nzmqt/include/nzmqt/nzmqt.hpp \
                Requester.hpp \
                pydiogui.h
SOURCES       = main.cpp \
                window.cpp \
                pydiogui.cpp
RESOURCES     = systray.qrc

QT += widgets \
      webkitwidgets

LIBS += -lzmq

# install
target.path = ./
INSTALLS += target

simulator: warning(This example might not fully work on Simulator platform)

INCLUDEPATH += \
    ../nzmqt/include \
    ../nzmqt/externals/include \
    $(QTDIR)/include \
    /usr/local/include

QMAKE_LIBDIR += \
    /usr/local/lib

FORMS += \
    pydiogui.ui
