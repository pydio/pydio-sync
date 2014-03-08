#include "pydiogui.h"
#include "ui_pydiogui.h"

PydioGui::PydioGui(QWidget *parent) :
    QWidget(parent),
    ui(new Ui::PydioGui)
{
    ui->setupUi(this);
}

PydioGui::~PydioGui()
{
    delete ui;
}
