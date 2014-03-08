#ifndef PYDIOGUI_H
#define PYDIOGUI_H

#include <QWidget>

namespace Ui {
class PydioGui;
}

class PydioGui : public QWidget
{
    Q_OBJECT

public:
    explicit PydioGui(QWidget *parent = 0);
    ~PydioGui();

private:
    Ui::PydioGui *ui;
};

#endif // PYDIOGUI_H
